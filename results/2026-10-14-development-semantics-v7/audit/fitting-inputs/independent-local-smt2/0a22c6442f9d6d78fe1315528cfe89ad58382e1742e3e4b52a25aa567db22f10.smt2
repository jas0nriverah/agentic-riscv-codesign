(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x10 (bvadd independent_opaque_1 (_ bv736 32))))
(let ((?x5 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x33 (bvadd ?x5 ?x10)))
(let ((?x28 (bvadd ?x10 ?x5)))
(and (distinct ?x28 ?x33) true))))))
(check-sat)
