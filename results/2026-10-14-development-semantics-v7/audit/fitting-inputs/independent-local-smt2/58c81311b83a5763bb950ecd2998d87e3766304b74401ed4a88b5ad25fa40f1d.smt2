(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x996 (bvshl independent_opaque_0 (bvand (_ bv25 32) (_ bv31 32)))))
(let ((?x48 (bvadd ?x996 independent_opaque_1)))
(let ((?x306 (bvadd independent_opaque_1 ?x996)))
(and (distinct ?x306 ?x48) true)))))
(check-sat)
