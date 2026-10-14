(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvadd independent_opaque_1 (_ bv5 32))))
(let ((?x329 (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x305 (bvadd ?x329 ?x38)))
(let ((?x276 (bvadd ?x38 ?x329)))
(and (distinct ?x276 ?x305) true))))))
(check-sat)
