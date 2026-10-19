(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x84 (bvadd independent_opaque_0 ?x38)))
(let ((?x334 (bvadd ?x38 independent_opaque_0)))
(and (distinct ?x334 ?x84) true)))))
(check-sat)
