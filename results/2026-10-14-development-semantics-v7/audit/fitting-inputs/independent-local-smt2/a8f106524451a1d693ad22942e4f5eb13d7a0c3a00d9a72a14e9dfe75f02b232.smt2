(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1140 (bvshl independent_opaque_0 (bvand (_ bv19 32) (_ bv31 32)))))
(let ((?x602 (bvadd ?x1140 independent_opaque_1)))
(let ((?x756 (bvadd independent_opaque_1 ?x1140)))
(and (distinct ?x756 ?x602) true)))))
(check-sat)
