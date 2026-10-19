(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x200 (bvshl y (_ bv17 32))))
(let ((?x196 (bvshl x (_ bv17 32))))
(let ((?x201 (bvadd ?x196 ?x200)))
(let ((?x19 (bvadd x y)))
(let ((?x199 (bvshl ?x19 (_ bv17 32))))
(and (distinct ?x199 ?x201) true)))))))
(check-sat)
