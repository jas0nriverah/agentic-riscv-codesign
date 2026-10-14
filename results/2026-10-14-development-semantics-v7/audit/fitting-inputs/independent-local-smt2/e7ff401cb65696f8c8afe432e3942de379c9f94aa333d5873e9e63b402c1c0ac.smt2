(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x74 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv31 32) (_ bv31 32)))) (bvsub (_ bv0 32) (bvshl independent_opaque_2 (bvand (_ bv31 32) (_ bv31 32)))))))
(let ((?x235 (bvadd independent_opaque_0 ?x74)))
(let ((?x52 (bvand (_ bv31 32) (_ bv31 32))))
(let ((?x56 (bvadd independent_opaque_0 (bvshl (bvsub independent_opaque_1 independent_opaque_2) ?x52))))
(and (distinct ?x56 ?x235) true))))))
(check-sat)
